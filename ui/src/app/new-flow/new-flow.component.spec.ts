import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { NewFlowComponent } from './new-flow.component'

describe('NewFlowComponent', () => {
    let component: NewFlowComponent
    let fixture: ComponentFixture<NewFlowComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [NewFlowComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(NewFlowComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
