import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { FlowResultsComponent } from './flow-results.component'

describe('FlowResultsComponent', () => {
    let component: FlowResultsComponent
    let fixture: ComponentFixture<FlowResultsComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [FlowResultsComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(FlowResultsComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
