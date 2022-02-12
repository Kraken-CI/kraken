import { ComponentFixture, TestBed } from '@angular/core/testing'

import { FlowPageComponent } from './flow-page.component'

describe('FlowPageComponent', () => {
    let component: FlowPageComponent
    let fixture: ComponentFixture<FlowPageComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [FlowPageComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(FlowPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
