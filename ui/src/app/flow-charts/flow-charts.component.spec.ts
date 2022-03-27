import { ComponentFixture, TestBed } from '@angular/core/testing'

import { FlowChartsComponent } from './flow-charts.component'

describe('FlowChartsComponent', () => {
    let component: FlowChartsComponent
    let fixture: ComponentFixture<FlowChartsComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [FlowChartsComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(FlowChartsComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
